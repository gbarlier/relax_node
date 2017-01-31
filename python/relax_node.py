# Copyright (c) 2013 Guillaume Barlier
# This file is part of "relax_node" and covered by the LGPLv3 or later,
# read COPYING and COPYING.LESSER for details.

# relax_node python plugin file for maya
#It performs a simple relax on mesh surfaces

from maya import cmds
from maya import OpenMaya
from maya import OpenMayaMPx

class RelaxNode(OpenMayaMPx.MPxDeformerNode):
    '''
    Relax geometry deformer
    Author: Guillaume Barlier
    '''
    
    # Default maya class attributes
    kPluginNodeId = OpenMaya.MTypeId(0xBA00100)
    kPluginNodeName = "relaxNode"

    # Custom inputs
    _strength_attr = OpenMaya.MObject()
    _iteration_attr = OpenMaya.MObject()
    _steps_attr = OpenMaya.MObject()
    
    def __init__(self):
        OpenMayaMPx.MPxDeformerNode.__init__(self)

    @classmethod
    def node_creator(cls):
        '''Maya API node creator
        '''
        return OpenMayaMPx.asMPxPtr( cls() )

    @classmethod
    def node_init(cls):
        '''Maya API node initialize
        '''
        double_attr_type = OpenMaya.MFnNumericAttribute()
        
        # Add strength setting attribute
        cls._strength_attr = double_attr_type.create( "strength", "str", OpenMaya.MFnNumericData.kFloat )
        double_attr_type.setKeyable( True )
        double_attr_type.setMin(0)
        double_attr_type.setMax(1)
        double_attr_type.setDefault(0.5)
        cls.addAttribute(cls._strength_attr)
        
        # Add iteration setting attribute
        cls._iteration_attr = double_attr_type.create( "iterations", "itr", OpenMaya.MFnNumericData.kInt )
        double_attr_type.setKeyable( True )
        double_attr_type.setMin(0)
        double_attr_type.setDefault(0)
        cls.addAttribute(cls._iteration_attr)
        
        # Add steps setting attribute
        cls._steps_attr = double_attr_type.create( "steps", "stp", OpenMaya.MFnNumericData.kInt )
        double_attr_type.setKeyable( True )
        double_attr_type.setMin(0)
        double_attr_type.setDefault(3)
        cls.addAttribute(cls._steps_attr)
        
        # Update affectation list
        outputGeom = OpenMayaMPx.cvar.MPxGeometryFilter_outputGeom
        cls.attributeAffects( cls._strength_attr, outputGeom )
        cls.attributeAffects( cls._iteration_attr, outputGeom )
        cls.attributeAffects( cls._steps_attr, outputGeom )
        
        # Make deformer weights paintable
        cmds.makePaintable(cls.kPluginNodeName, 'weights', attrType='multiFloat', shapeMode='deformer')
#        OpenMaya.MGlobal.executeCommand( "makePaintable -attrType multiFloat -sm deformer %S weights"%cls.kPluginNodeName )
    
    def get_input_mesh(self, data, geom_index):
        '''Return input mesh for geometry input index
        '''
        input_attr_handle = data.outputArrayValue( self.input )
        input_attr_handle.jumpToElement( geom_index )
        geom_handle = input_attr_handle.outputValue().child( self.inputGeom )
        input_geom = geom_handle.asMesh()
        
        return input_geom
    
    def get_component_average_position(self, vtx_index):
        '''Will return component neighbors average position
        '''
        # Set iterator index
        util = OpenMaya.MScriptUtil()
        util.createFromInt(0)
        prev_ptr = util.asIntPtr()
        self.vtx_iterator.setIndex(vtx_index, prev_ptr)
        
        # Get connected vertices
        vertices = OpenMaya.MIntArray()
        self.vtx_iterator.getConnectedVertices(vertices)
        
        # Get total position
        total_pos = OpenMaya.MPoint()
        for j in vertices:
            total_pos += OpenMaya.MVector(self.all_positions[j])
        
        # Return averaged position
        return total_pos/vertices.length()
    
    def get_weighted_componenents(self, geom_iter, geom_index, data):
        '''Return a dictionary a weighted components index and weights
        '''
        # Init weight dictionary
        weights = dict()
        
        # Parse components
        while not geom_iter.isDone():
            index = geom_iter.index()
            
            # Get current component deformer weight
            weight = self.weightValue(data, geom_index, index)

            # Store component index and related weight
            if weight:
               weights[index] =  weight
            
            # Move to next
            geom_iter.next()

        return weights
            
    def deform(self,
               data, # dataBlock
               geom_iter, # geom iteration class instance
               matrix, # local to worl matrix
               geom_index):
        '''Compute relax and apply to geometry
        '''
        # Get setting values
        env_value = data.inputValue(self.envelope).asFloat()
        if not env_value:
            return False
        
        iter_value = data.inputValue(self._iteration_attr).asInt()
        if not iter_value:
            return False
        
        steps_value = data.inputValue(self._steps_attr).asInt()
        if not steps_value:
            return False
        
        strength_value = data.inputValue(self._strength_attr).asFloat()
        if not strength_value:
            return False
        
        # Get weighted components
        comp_weight_data = self.get_weighted_componenents(geom_iter, geom_index, data)
        if not comp_weight_data:
            return False
        
        # Get input mesh
        input_mesh = self.get_input_mesh(data, geom_index)
        
        # Get polygon iteration tool
        self.vtx_iterator = OpenMaya.MItMeshVertex(input_mesh)
        
        # Get all start positions
        self.all_positions = OpenMaya.MPointArray()
        geom_iter.allPositions(self.all_positions)
        
        # Compute deformation
        for i in range(iter_value):
            for step in range(steps_value):
                # Init new position array
                new_positions = OpenMaya.MPointArray(self.all_positions)
                new_positions.copy(self.all_positions)
                
                for index in comp_weight_data:
                    # Get current component weight and position
                    weight = comp_weight_data[index]
                    current_pos = self.all_positions[index]

                    # Get average position
                    average_pos = self.get_component_average_position(index)

                    # Compute new component position
                    offset_pos = (average_pos - current_pos) * weight * env_value * strength_value
                    new_pos = current_pos + offset_pos / (steps_value - step)

                    # Update new position
                    new_positions.set(new_pos, index)
                
                # Update stored position for next iteration
                self.all_positions.copy(new_positions)

        # Set new positions:
        geom_iter.setAllPositions(self.all_positions)
        
        return True


# initialize the script plug-in
def initializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        mplugin.registerNode( RelaxNode.kPluginNodeName,
                              RelaxNode.kPluginNodeId,
                              RelaxNode.node_creator,
                              RelaxNode.node_init,
                              OpenMayaMPx.MPxNode.kDeformerNode )
    except:
        raise "Failed to register node: %s" % RelaxNode.kPluginNodeName

# uninitialize the script plug-in
def uninitializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        mplugin.deregisterNode( RelaxNode.kPluginNodeId )
    except:
        raise "Failed to deregister node: %s" % RelaxNode.kPluginNodeName

