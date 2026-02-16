using Assets.Scripts.ResourceHandlers;
using Assets.Scripts.Resources;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using CommunityToolkit.HighPerformance.Helpers;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.XR;

namespace Assets.Scripts
{
	public class InstanceVar
	{
		public MetaModel.MM_Variable Variable;
		public object Value;
	}

    class MetaModelInstance : MonoBehaviour
    {
	    private static List<string> TSGShaders = new List<string>()
	    {
		    "simpsons_chocolate",
		    "simpsons_vfx_rigid_textured",
		    "simpsons_rigid_normalmap",
		    "simpsons_rigid_multitone",
		    "simpsons_projtex",
		    "simpsons_rigid_dualtextured_uv",
		    "simpsons_skin_dualtextured_uv",
		    "simpsons_uv",
		    "simpsons_skin_flipbook",
		    "simpsons_flipbook",
		    "simpsons_sky",
		    "simpsons_skin_gloss",
		    "simpsons_rigid_gloss",
		    "simpsons_rigid_dualtextured",
		    "simpsons_skin_dualtextured",
		    "simpsons_rigid_textured",
		    "simpsons_skin_textured",
		    "simpsons_aa_col",
		    "simpsons_aa_row",
		    "simpsons_edgeAA",
		    "simpsons_aa",
		    "simpsons_edge",
		    "simpsons_rigid",
		    "simpsons_skin"
	    };

	    private static Dictionary<uint, string> HashToShader = new();

		public MetaModel MetaModel;
	    public InstanceVar[] Vars;

	    public void Assign(MetaModel metaModel)
	    {
		    MetaModel = metaModel;

		    Vars = new InstanceVar[metaModel.m_nVariables];
		    for (var i = 0; i < metaModel.m_nVariables; i++)
		    {
			    var iv = new InstanceVar();
			    iv.Variable = metaModel.Variables[i];

			    switch (iv.Variable.m_valueType)
			    {
					case MetaModel.MM_ValueType.BOOL:
						iv.Value = false;
						break;
					case MetaModel.MM_ValueType.UINT32:
						iv.Value = 0u;
						break;
					case MetaModel.MM_ValueType.FLOAT:
						iv.Value = 0.0f;
						break;
					default:
						throw new NotImplementedException();
			    }

			    Vars[i] = iv;
		    }

			CheckStates();
	    }

	    public void CheckStates()
	    {
		    if (MetaModel == null)
		    {
			    throw new NotImplementedException();
		    }

		    if (MetaModel.m_nStates == 0)
		    {
			    ClearState();
			    return;
		    }

			//Debug.Log($"Checking states for {this}", this);
			MetaModel.MM_State passingState = null;
		    for (var i = 0; i < MetaModel.m_nStates; i++)
		    {
			    var pass = true;

				//Debug.Log($"State {i+1}/{MetaModel.m_nStates}");
				var state = MetaModel.States[i];
			    for (var j = 0; j < state.m_nPredicates; j++)
			    {
				    //Debug.Log($"- Predicate {j + 1}/{state.m_nPredicates}");
					var predicate = state.m_pPredicateArr[j];
				    if (predicate.m_pVariable == null)
				    {
					    throw new NotImplementedException();
				    }

				    
				    var variable = predicate.m_pVariable;

				    var instanceVariable = Vars.First(x => x.Variable == variable);

				    switch (variable.m_valueType)
				    {
						case MetaModel.MM_ValueType.BOOL:
							pass = pass && Compare((bool)instanceVariable.Value, predicate.GetBool(), predicate.m_compareOp);
							break;
						case MetaModel.MM_ValueType.UINT32:
							pass = pass && Compare((uint)instanceVariable.Value, predicate.GetUInt(), predicate.m_compareOp);
							break;
						case MetaModel.MM_ValueType.FLOAT:
							pass = pass && Compare((float)instanceVariable.Value, predicate.GetFloat(), predicate.m_compareOp);
							break;
					}
			    }

			    if (pass)
			    {
				    passingState = state;
					break;
			    }
		    }

		    if (passingState == null)
		    {
			    Debug.LogError("No states passed! Choosing first state...", this);
			    passingState = MetaModel.States[0];
		    }

			ChangeState(passingState);
	    }

	    public void ChangeState(MetaModel.MM_State newState)
	    {
		    //Debug.Log($"Changing to state {newState.m_pName}", this);

		    foreach (var part in newState.m_pPartArr)
		    {
			    if (part.m_classID == 835904732)
			    {
				    // ModelPart

				    var parent = new GameObject(part.m_pName);
				    parent.transform.parent = transform;
				    parent.transform.localPosition = Vector3.zero;
				    parent.transform.localRotation = Quaternion.identity;
				    parent.transform.localScale = Vector3.one;

				    foreach (var attr in part.m_pAttributeArr)
				    {
					    if (attr.m_pName == "CMD_LoadMatrix")
					    {
						    var matrix = attr.GetMatrix();
						    var trs = matrix.GetTRS();

						    parent.transform.localPosition = trs.position;
						    parent.transform.localRotation = trs.rotation;
						    parent.transform.localScale = trs.scale;
					    }
					    else if (attr.m_pName == "Model")
					    {
						    var asset = attr.GetAsset();
						    var resource = ResourceHandlerManager.FindResourceById(asset.m_GUID);

						    if (resource is not EARS_MESH readFile)
						    {
							    Debug.LogError($"Resource is not EARS_MESH! Type: {resource.GetType().Name}", this);
							    Debug.Break();
							    return;
						    }

						    if (HashToShader.Count == 0)
						    {
							    foreach (var item in TSGShaders)
							    {
								    var hash = new SDBMHash(item);
								    HashToShader.Add(hash.Value, item);
								    //Debug.Log($"{item} : {hash}");
							    }
						    }

						    var splitMeshes = readFile.GetMeshes();

						    foreach (var splitMesh in splitMeshes)
						    {
							    var textures = MaterialManager.Instance.GetTextures(splitMesh.Material);

							    var meshObj = new GameObject(splitMesh.UnityMesh.name + $"Shader:{HashToShader[splitMesh.Shader]}, Textures:{textures.Length}, UV Sets:{splitMesh.UVCount}");
							    var mf = meshObj.AddComponent<MeshFilter>();
							    mf.sharedMesh = splitMesh.UnityMesh;

							    var renderer = meshObj.AddComponent<MeshRenderer>();
							    renderer.material = MaterialManager.Instance.CreateMaterialInstance(
								    splitMesh.Shader, textures);

							    meshObj.transform.parent = parent.transform;
							    meshObj.transform.localScale = new Vector3(1, 1, 1);
							    meshObj.transform.localPosition = Vector3.zero;
							    meshObj.transform.localRotation = Quaternion.identity;
						    }
						}
					    else
					    {
							Debug.LogWarning($"Unknown ModelPart attribute {attr.m_pName}");
					    }
					}
				}
				else if (part.m_classID == 583326711)
				{
					// MetaModelPart

					var parent = new GameObject(part.m_pName);
					parent.transform.parent = transform;
					parent.transform.localPosition = Vector3.zero;
					parent.transform.localRotation = Quaternion.identity;
					parent.transform.localScale = Vector3.one;

					foreach (var attr in part.m_pAttributeArr)
					{
						if (attr.m_pName == "CMD_LoadMatrix")
						{
							var matrix = attr.GetMatrix();
							var trs = matrix.GetTRS();

							parent.transform.localPosition = trs.position;
							parent.transform.localRotation = trs.rotation;
							parent.transform.localScale = trs.scale;
						}
						else if (attr.m_pName == "fileName")
						{
							var asset = attr.GetAsset();
							var resource = ResourceHandlerManager.FindResourceById(asset.m_GUID);

							if (resource is not MetaModel mm)
							{
								Debug.LogError($"Resource is not MetaModel! Type: {resource.GetType().Name}", this);
								Debug.Break();
								return;
							}

							var comp = parent.AddComponent<MetaModelInstance>();
							comp.Assign(mm);
						}
					}
				}
				else if (part.m_classID == 4017522427)
				{
					// VFXPart
				}
				else if (part.m_classID == 3871761413)
				{
					// CollisionPart
				}
				else
				{
					Debug.LogWarning($"Unknown part class type {part.m_classID} {part.m_pClassName}");
				}
		    }
		}

	    public bool Compare(bool a, bool b, MetaModel.CompareOp compareOp)
	    {
		    return Compare(a ? (byte)1 : (byte)0, b ? (byte)1 : (byte)0, compareOp);
	    }

		public bool Compare(uint a, uint b, MetaModel.CompareOp compareOp)
	    {
		    switch (compareOp)
		    {
			    case MetaModel.CompareOp.GT:
				    return a > b;
			    case MetaModel.CompareOp.LT:
				    return a < b;
			    case MetaModel.CompareOp.GE:
				    return a >= b;
			    case MetaModel.CompareOp.LE:
				    return a <= b;
			    case MetaModel.CompareOp.EQ:
				    return a == b;
			    case MetaModel.CompareOp.NEQ:
				    return a != b;
			    default:
				    throw new ArgumentOutOfRangeException(nameof(compareOp), compareOp, null);
		    }
	    }

	    public bool Compare(float a, float b, MetaModel.CompareOp compareOp)
	    {
		    switch (compareOp)
		    {
			    case MetaModel.CompareOp.GT:
				    return a > b;
			    case MetaModel.CompareOp.LT:
				    return a < b;
			    case MetaModel.CompareOp.GE:
				    return a >= b;
			    case MetaModel.CompareOp.LE:
				    return a <= b;
			    case MetaModel.CompareOp.EQ:
				    return a == b;
			    case MetaModel.CompareOp.NEQ:
				    return a != b;
			    default:
				    throw new ArgumentOutOfRangeException(nameof(compareOp), compareOp, null);
		    }
	    }

		public void ClearState()
	    {
		    throw new NotImplementedException();
	    }
    }
}
